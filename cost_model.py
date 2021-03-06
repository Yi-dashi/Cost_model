import torch
import torch.nn as nn
import math
#from mypath import Path
import torch.utils.model_zoo as model_zoo

from torch.nn import functional as F

__all__ = ['ResNet', 'resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152']


model_urls = {
    'resnet18': 'https://download.pytorch.org/models/resnet18-5c106cde.pth',
    'resnet34': 'https://download.pytorch.org/models/resnet34-333f7ec4.pth',
    'resnet50': 'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    'resnet101': 'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
    'resnet152': 'https://download.pytorch.org/models/resnet152-b121ed2d.pth',
}


class attentionblock(nn.Module):
    def __init__(self,in_channel):
        super(attentionblock, self).__init__()
        #self.num_classes=num_classes
        self.pool = nn.AdaptiveMaxPool3d(1)
        self.in_channel = in_channel
        self.conv = nn.Conv3d(self.in_channel, self.in_channel, kernel_size=(1, 1, 1))
        self.linear = nn.Linear(self.in_channel * 3, self.in_channel * 3)
        #print(self.linear)
    def forward(self, input1, input2, input3):
        #print(input1.shape,"inpu1")
        #print(input2.shape,"input2")
        input1 = self.pool(input1)
        input2 = self.pool(input2)
        input3 = self.pool(input3)
        input1 = self.conv(input1)
        input2 = self.conv(input2)
        input3 = self.conv(input3)
        input1 = input1.squeeze()
        input2 = input2.squeeze()
        input3 = input3.squeeze()
        #print(input1.shape,"inpu1")
        #print(input2.shape,"inpu2")
        #print(input3.shape,"inpu3")
        a = torch.cat((input1, input2, input3), 1)
        #print(a.shape)
        a = self.linear(a)
        #print(a.shape,"attena")
        a = F.softmax(a, dim = 0)
        return a
class costblock(nn.Module):
    def __init__(self, in_channel, channel, stride = 1):
        super(costblock, self).__init__()
        #self.size=size
        self.stride = stride
        #self.num_classes=num_classes
        self.in_channel = in_channel
        self.channel = channel
        self.bn1 = nn.BatchNorm3d(self.channel)
        self.bn2 = nn.BatchNorm3d(self.channel * 4)
        #self.stride=stride
        self.conv1 = nn.Conv3d(self.in_channel, self.channel, kernel_size = (1, 1, 1))
        self.conv = nn.Conv2d(self.channel, self.channel, kernel_size = (3, 3),padding = (1, 1),stride = (self.stride, self.stride))
        self.conv2 = nn.Conv3d(self.channel, self.channel * 4, kernel_size = (1, 1, 1))
        self.attenblock = attentionblock(self.channel)
        self.relu = nn.ReLU(inplace = True)
        self.batchnorm = nn.BatchNorm2d(self.channel)
        self.downsample = nn.Sequential()
        if self.stride != 1 or self.in_channel != self.channel * 4:
            self.downsample = nn.Sequential(
                nn.Conv3d(self.in_channel, self.channel * 4, kernel_size=1, stride=(1, self.stride, self.stride), bias = False),
                nn.BatchNorm3d(self.channel * 4)
            )
    def forward(self, input):
        shortcut =self.downsample(input)
        #print(shortcut.shape)
        input = self.conv1(input)
        input = self.bn1(input)
        input = self.relu(input)
        x1 = input.view(input.shape[0], input.shape[1], input.shape[2], input.shape[3] * input.shape[4])
        x2 = input.transpose(2, 3)
        x2 = x2.contiguous().view(x2.shape[0], x2.shape[1], x2.shape[2], x2.shape[3] * x2.shape[4])
        x3 = input.transpose(2, 4)
        x3 = x3.contiguous().view(x3.shape[0], x3.shape[1], x3.shape[2], x3.shape[3] * x3.shape[4])
        #print(input.shape[3])
        #out1=self.conv(x1).view(input.shape[0],input.shape[1],input.shape[2],int(input.shape[3]/self.stride),int(input.shape[4]/self.stride))
        #out1=self.batchnorm(out1)
        #out1=self.relu(out1)
        #out2=self.conv(x2).view(input.shape[0],input.shape[1],input.shape[2],int(input.shape[3]/self.stride),int(input.shape[4]/self.stride))
        #out3=self.conv(x3).view(input.shape[0],input.shape[1],input.shape[2],int(input.shape[3]/self.stride),int(input.shape[4]/self.stride))

        out1 = self.conv(x1)
        out1 = self.batchnorm(out1)
        out1 = self.relu(out1)
        out1 = out1.view(input.shape[0], input.shape[1], input.shape[2], int(input.shape[3]/self.stride), int(input.shape[4]/self.stride))
        out2 = self.conv(x2)
        out2 = self.batchnorm(out2)
        out2 = self.relu(out2)
        out2 = out2.view(input.shape[0], input.shape[1], input.shape[2], int(input.shape[3] / self.stride), int(input.shape[4] / self.stride))
        out3 = self.conv(x3)
        out3 = self.batchnorm(out3)
        out3 = self.relu(out3)
        out3 = out3.view(input.shape[0], input.shape[1], input.shape[2], int(input.shape[3] / self.stride), int(input.shape[4] / self.stride))
        #out=torch.cat((out1,out2,out3),1)
        a=self.attenblock(out1, out2, out3)

        a1,a2,a3 = a.chunk(3, dim=1)

        output1 = out1.permute(2, 3, 4, 0, 1) * a1 + out2.permute(2, 3, 4, 0, 1) * a2 + out3.permute(2, 3, 4, 0, 1) * a3
        output1 = output1.permute(3, 4, 0, 1, 2)
        output1 = self.conv2(output1)
        output1 = self.bn2(output1)
        #print(output1.shape)
        output1 = output1 + shortcut
        output1 = self.relu(output1)
        return output1

class Cost(nn.Module):
    """
    The Cost network.
    """

    def __init__(self, num_classes,block, layers,pretrained=False):
        super(Cost, self).__init__()

        self.in_channels=64
        self.conv1 = nn.Conv3d(3, 64, kernel_size=(3, 7, 7), stride=(1, 2, 2), padding=(1, 3, 3), bias=False)
        self.bn1 = nn.BatchNorm3d(64)
        self.relu = nn.ReLU(inplace=True)
        self.max_pool = nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(1, 2, 2), padding=(0, 1, 1))

        self.layer1 = self._make_layer(block, 64, layers[0], stride=1)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        self.avg_pool = nn.AdaptiveAvgPool3d(1)
        self.dropout = nn.Dropout(p=0.5)
        #self.fc = nn.Linear(512 * 4, num_classes)
        self.fc1 = nn.Linear(2048, 1024)
        self.fc2 = nn.Linear(1024, 1024)
        self.fc3 = nn.Linear(1024, num_classes)
        self.__init_weight()

    def forward(self, x):

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.max_pool(out)
        #print(out.shape)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)

        out = self.avg_pool(out)
        out = out.view(out.size(0), -1)
        #out = self.fc(out)
        out = self.relu(self.fc1(out))
        out = self.dropout(out)
        out = self.relu(self.fc2(out))
        out = self.dropout(out)

        out = self.fc3(out)
        return out

    def _make_layer(self, block, channels, n_blocks, stride=1):
        assert n_blocks > 0, "number of blocks should be greater than zero"
        layers = []
        layers.append(block(self.in_channels, channels, stride))
        self.in_channels = channels * 4
        for i in range(1, n_blocks):
            layers.append(block(self.in_channels, channels))

        return nn.Sequential(*layers)

    def __init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                # n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                # m.weight.data.normal_(0, math.sqrt(2. / n))
                torch.nn.init.kaiming_normal_(m.weight)
            
            elif isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()            
            elif isinstance(m, nn.BatchNorm3d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
def get_1x_lr_params(model):
    """
    This generator returns all the parameters for conv and two fc layers of the net.
    """
    b = [model.conv1, model.layer1, model.layer2, model.layer3, model.layer4, model.fc1,
         model.fc2]
    for i in range(len(b)):
        for k in b[i].parameters():
            if k.requires_grad:
                yield k

def get_10x_lr_params(model):
    """
    This generator returns all the parameters for the last fc layer of the net.
    """
    b = [model.fc3]
    for j in range(len(b)):
        for k in b[j].parameters():
            if k.requires_grad:
                yield k

def cost50(pretrained=Flase):
    """Constructs a Cost-Res50 model.
    Args:
        pretrained (bool): IF Ture,returns a model pre-trained on ImageNet
    """
    model = Cost(costmodel, [3, 4, 6, 3])
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet50']), strict = Flase)
    return model

def cost101(pretrained=Flase, **kwargs):
    """Constructs a Cost-Res101 model.
    Args:
        pretrained (bool):IF Ture,returns a model pre-trained on ImageNet
    """
    model = Cost(costmodel, [3, 4, 23, 3], **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet101']), strict = Flase)
    return model

if __name__ == "__main__":
    inputs = torch.rand(2, 3, 16, 224, 224)
    net=Cost(101,costblock, [3,4,6,3])
    #net = costblock(64,64,stride=2)
    print(net.layer4[1].conv.weight.grad)
    outputs = net(inputs)
    print(outputs.size())
