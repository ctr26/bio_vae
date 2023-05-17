# https://github.com/AntixK/PyTorch-VAE

#                  Apache License
#            Version 2.0, January 2004
#         http://www.apache.org/licenses/
# Copyright Anand Krishnamoorthy Subramanian 2020
#            anandkrish894@gmail.com
import torch
from .utils import BaseVAE
from torch import nn
from torch.nn import functional as F
from .types_ import *

from pythae.models.nn import BaseEncoder, BaseDecoder
from pythae.models.base.base_utils import ModelOutput

def encoder_layers(channels, hidden_dims):
        modules = []

        for h_dim in hidden_dims:
            modules.append(
                nn.Sequential(
                    nn.Conv2d(
                        channels,
                        out_channels=h_dim,
                        kernel_size=3,
                        stride=2,
                        padding=1,
                    ),
                    nn.BatchNorm2d(h_dim),
                    nn.LeakyReLU(),
                )
            )
            channels = h_dim
        return nn.Sequential(*modules)


def decoder_layers(channels, hidden_dims):
        modules = []
        for i in range(len(hidden_dims) - 1):
            modules.append(
                nn.Sequential(
                    nn.ConvTranspose2d(
                        hidden_dims[i],
                        hidden_dims[i + 1],
                        kernel_size=3,
                        stride=2,
                        padding=1,
                        output_padding=1,
                    ),
                    nn.BatchNorm2d(hidden_dims[i + 1]),
                    nn.LeakyReLU(),
                )
            )
        final_layer = nn.Sequential(
            nn.ConvTranspose2d(
                hidden_dims[-1],
                hidden_dims[-1],
                kernel_size=3,
                stride=2,
                padding=1,
                output_padding=1,
            ),
            nn.BatchNorm2d(hidden_dims[-1]),
            nn.LeakyReLU(),
            nn.Conv2d(
                hidden_dims[-1], out_channels=channels, kernel_size=3, padding=1
            ),
            nn.Tanh(),
        )
        return nn.Sequential(*modules, final_layer)
    
class Encoder(BaseEncoder):
    def __init__(self, model_config, hidden_dims=[32, 64, 128, 256, 512]):
        BaseEncoder.__init__(self)

        self.input_dim = model_config.input_dim
        self.latent_dim = model_config.latent_dim
        self.channels = self.input_dim[0]
        self.image_dims = self.input_dim[1:]
    
        self.hidden_dims = hidden_dims
        
        self.latent_input_dim = torch.tensor(self.image_dims) / 2 ** (len(hidden_dims))
        self.latent_input_dim_len = int(torch.prod(self.latent_input_dim.flatten(), 0))
        # Build Encoder

        self.conv_layers = encoder_layers(self.channels, hidden_dims)
        self.embedding = nn.Linear(
            hidden_dims[-1] * self.latent_input_dim_len, self.latent_dim
        )
        self.log_var = nn.Linear(
            hidden_dims[-1] * self.latent_input_dim_len, self.latent_dim
        )

    

    def forward(self, x: torch.Tensor):
        h1 = self.conv_layers(x).reshape(x.shape[0], -1)
        output = ModelOutput(
            embedding=self.embedding(h1), log_covariance=self.log_var(h1)
        )
        return output


class Decoder(BaseDecoder):
    def __init__(self, model_config, hidden_dims=[32, 64, 128, 256, 512]):
        BaseDecoder.__init__(self)
        self.input_dim = model_config.input_dim
        self.latent_dim = model_config.latent_dim
        self.channels = self.input_dim[0]
        self.image_dims = self.input_dim[1:]
        hidden_dims = hidden_dims
        self.hidden_dims = hidden_dims

        self.latent_input_dim = torch.tensor(self.image_dims) / 2 ** (len(hidden_dims))
        self.latent_input_dim_len = int(torch.prod(self.latent_input_dim.flatten(), 0))
        self.fc = nn.Linear(self.latent_dim, self.latent_input_dim_len)

        self.decoder_input = nn.Linear(
            self.latent_dim, hidden_dims[-1] * self.latent_input_dim_len
        )
        # self.fc = self.decoder_input

        self.deconv_layers = decoder_layers(self.channels, hidden_dims[::-1])
    

    def forward(self, z: torch.Tensor):
        # h1 = self.fc(z)
        h1 = self.decoder_input(z).view(
            -1,
            self.hidden_dims[-1],
            int(self.latent_input_dim[-1]),
            int(self.latent_input_dim[0]),
        )
        return ModelOutput(reconstruction=self.deconv_layers(h1))


class VAE(BaseVAE):
    def __init__(
        self,
        in_channels: int,
        latent_dim: int,
        hidden_dims: List = None,
        image_dims=(64, 64),
        **kwargs
    ) -> None:
        super(VAE, self).__init__()

        self.latent_dim = latent_dim

        modules = []
        if hidden_dims is None:
            hidden_dims = [32, 64, 128, 256, 512]

        self.channels = in_channels
        self.hidden_dims = hidden_dims
        # Build Encoder

        for h_dim in hidden_dims:
            modules.append(
                nn.Sequential(
                    nn.Conv2d(
                        in_channels,
                        out_channels=h_dim,
                        kernel_size=3,
                        stride=2,
                        padding=1,
                    ),
                    nn.BatchNorm2d(h_dim),
                    nn.LeakyReLU(),
                )
            )
            in_channels = h_dim

        self.encoder = nn.Sequential(*modules)
        self.latent_input_dim = torch.tensor(image_dims) / 2 ** (len(hidden_dims))
        self.latent_input_dim_len = int(torch.prod(self.latent_input_dim.flatten(), 0))
        # input_test = torch.randn((1,self.channels,128,128))
        # self.encoder(input_test)
        self.fc_mu = nn.Linear(hidden_dims[-1] * self.latent_input_dim_len, latent_dim)
        self.fc_var = nn.Linear(hidden_dims[-1] * self.latent_input_dim_len, latent_dim)

        # Build Decoder
        modules = []

        self.decoder_input = nn.Linear(
            latent_dim, hidden_dims[-1] * self.latent_input_dim_len
        )

        hidden_dims.reverse()

        for i in range(len(hidden_dims) - 1):
            modules.append(
                nn.Sequential(
                    nn.ConvTranspose2d(
                        hidden_dims[i],
                        hidden_dims[i + 1],
                        kernel_size=3,
                        stride=2,
                        padding=1,
                        output_padding=1,
                    ),
                    nn.BatchNorm2d(hidden_dims[i + 1]),
                    nn.LeakyReLU(),
                )
            )

        self.decoder = nn.Sequential(*modules)

        self.final_layer = nn.Sequential(
            nn.ConvTranspose2d(
                hidden_dims[-1],
                hidden_dims[-1],
                kernel_size=3,
                stride=2,
                padding=1,
                output_padding=1,
            ),
            nn.BatchNorm2d(hidden_dims[-1]),
            nn.LeakyReLU(),
            nn.Conv2d(
                hidden_dims[-1], out_channels=self.channels, kernel_size=3, padding=1
            ),
            nn.Tanh(),
        )
        
    def update(self):
        pass
    
    def encode(self, input: Tensor) -> List[Tensor]:
        """
        Encodes the input by passing through the encoder network
        and returns the latent codes.
        :param input: (Tensor) Input tensor to encoder [N x C x H x W]
        :return: (Tensor) List of latent codes
        """
        result = self.encoder(input)
        result = torch.flatten(result, start_dim=1)

        # Split the result into mu and var components
        # of the latent Gaussian distribution
        mu = self.fc_mu(result)
        log_var = self.fc_var(result)

        return [mu, log_var]

    def decode(self, z: Tensor) -> Tensor:
        """
        Maps the given latent codes
        onto the image space.
        :param z: (Tensor) [B x D]
        :return: (Tensor) [B x C x H x W]
        """
        result = self.decoder_input(z)
        result = result.view(
            -1,
            self.hidden_dims[0],
            int(self.latent_input_dim[-1]),
            int(self.latent_input_dim[0]),
        )
        result = self.decoder(result)
        result = self.final_layer(result)
        return result

    def reparameterize(self, mu: Tensor, logvar: Tensor) -> Tensor:
        """
        Reparameterization trick to sample from N(mu, var) from
        N(0,1).
        :param mu: (Tensor) Mean of the latent Gaussian [B x D]
        :param logvar: (Tensor) Standard deviation of the latent Gaussian [B x D]
        :return: (Tensor) [B x D]
        """
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return eps * std + mu

    def forward(self, input: Tensor, **kwargs) -> List[Tensor]:
        mu, log_var = self.encode(input)
        z = self.reparameterize(mu, log_var)
        return [self.decode(z), input, mu, log_var]

    def recon(self, x):
        x_recon, input, mu, log_var = self.forward(x)
        return x_recon

    def loss_function(self, *args, **kwargs) -> dict:
        """
        Computes the VAE loss function.
        KL(N(\mu, \sigma), N(0, 1)) = \log \frac{1}{\sigma} + \frac{\sigma^2 + \mu^2}{2} - \frac{1}{2}
        :param args:
        :param kwargs:
        :return:
        """
        recons = args[0]
        input = args[1]
        mu = args[2]
        log_var = args[3]

        kld_weight = 0.00025  # Account for the minibatch samples from the dataset
        recons_loss = F.mse_loss(recons, input)

        kld_loss = torch.mean(
            -0.5 * torch.sum(1 + log_var - mu**2 - log_var.exp(), dim=1), dim=0
        )

        loss = recons_loss + kld_weight * kld_loss
        return {
            "loss": loss,
            "Reconstruction_Loss": recons_loss.detach(),
            "KLD": -kld_loss.detach(),
        }

    def sample(self, num_samples: int, **kwargs) -> Tensor:
        """
        Samples from the latent space and return the corresponding
        image space map.
        :param num_samples: (Int) Number of samples
        :param current_device: (Int) Device to run the model
        :return: (Tensor)
        """
        z = torch.randn(num_samples, self.latent_dim)

        # z = z.to(current_device)

        samples = self.decode(z)
        return samples

    def generate(self, x: Tensor, **kwargs) -> Tensor:
        """
        Given an input image x, returns the reconstructed image
        :param x: (Tensor) [B x C x H x W]
        :return: (Tensor) [B x C x H x W]
        """

        return self.forward(x)[0]

    def output_from_results(self, x_recon, input, mu, log_var):
        """
        Given an input image x, returns the reconstructed image
        :param x: (Tensor) [B x C x H x W]
        :return: (Tensor) [B x C x H x W]
        """
        return x_recon
